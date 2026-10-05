# VRAM and GTT readings across every discrete GPU. Sourced, not run:
#
#   . "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/gpu-mem.sh"
#
# Added 2026-10-05 with the R9700. Until then every script read
# /sys/class/drm/card1, the only dGPU. Two things broke that:
#
#   * llama.cpp splits layers across all GPUs by default, with no flag, so one
#     card's reading is a fraction of the real use. Qwen3.8-27B IQ4_XS at 32K
#     put 10.9 GB on the R9700 and 5.5 GB on the 9070 XT.
#   * DRM numbering is assigned at boot, not by slot. The R9700 took card0 and
#     the 9070 XT kept card1 by luck. Nothing here may assume an index.
#
# A card counts as discrete when it has more than 2 GiB of VRAM. That drops the
# 9800X3D iGPU, whose 512 MiB is a carve-out from host RAM and which llama.cpp
# does not use for compute (ddr5-9800x3d.md).
#
# Index order (card0, card1, ...) is DRM's, and is NOT llama.cpp's: ROCm0 is
# the 9070 XT, ROCm1 the R9700. Label output by name, never by index.

GPU_DEVS=()
for _d in /sys/class/drm/card[0-9]*; do
  [[ $(basename "$_d") =~ ^card[0-9]+$ ]] || continue          # skip card0-DP-3 etc.
  _t=$(cat "$_d/device/mem_info_vram_total" 2>/dev/null) || continue
  (( _t > 2147483648 )) && GPU_DEVS+=("$_d/device")
done
unset _d _t
if (( ${#GPU_DEVS[@]} == 0 )); then
  echo "gpu-mem.sh: no discrete GPU under /sys/class/drm" >&2
  return 1 2>/dev/null || exit 1
fi

# Short name for card $1 (an index into GPU_DEVS), from the PCI device ID.
gpu_name() {
  case $(cat "${GPU_DEVS[$1]}/device") in
    0x7550) echo 9070XT ;;
    0x7551) echo R9700 ;;
    *)      basename "$(dirname "${GPU_DEVS[$1]}")" ;;
  esac
}

# One card's reading in MiB: gpu_mib <index> vram_used|vram_total|gtt_used
gpu_mib() { echo $(( $(cat "${GPU_DEVS[$1]}/mem_info_$2") / 1048576 )); }

# Summed across every discrete card, in MiB.
_gpu_sum() { local i s=0; for i in "${!GPU_DEVS[@]}"; do s=$(( s + $(gpu_mib "$i" "$1") )); done; echo "$s"; }
vram_used()  { _gpu_sum vram_used; }
vram_total() { _gpu_sum vram_total; }
gtt_used()   { _gpu_sum gtt_used; }

# True when every card is below $1 MiB (default 900). Per card, not summed: the
# desktop sits on one card, and a sum would hide a model left on the other.
vram_idle() {
  local i
  for i in "${!GPU_DEVS[@]}"; do (( $(gpu_mib "$i" vram_used) < ${1:-900} )) || return 1; done
}

# "R9700 10885/32624 + 9070XT 5479/16304 = 16364/48928 MiB"
vram_report() {
  local i out=""
  for i in "${!GPU_DEVS[@]}"; do
    out+="${out:+ + }$(gpu_name "$i") $(gpu_mib "$i" vram_used)/$(gpu_mib "$i" vram_total)"
  done
  (( ${#GPU_DEVS[@]} > 1 )) && out+=" = $(vram_used)/$(vram_total)"
  echo "$out MiB"
}
