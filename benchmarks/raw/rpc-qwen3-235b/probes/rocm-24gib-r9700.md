| model                          |       size |     params | backend    | ngl |  fa | dev          | ts           |         lm |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | --: | ------------ | ------------ | ---------: | --------------: | -------------------: |
| qwen3moe 235B.A22B Q3_K - Medium |  96.99 GiB |   235.09 B | ROCm,RPC   |  99 |   1 | ROCm0/ROCm1/RPC0/RPC1 | 11.00/23.00/8.00/52.00 |       none |            pp64 |         34.68 ± 0.00 |
| qwen3moe 235B.A22B Q3_K - Medium |  96.99 GiB |   235.09 B | ROCm,RPC   |  99 |   1 | ROCm0/ROCm1/RPC0/RPC1 | 11.00/23.00/8.00/52.00 |       none |            tg16 |          5.08 ± 0.00 |

build: b94959a64 (12557)
