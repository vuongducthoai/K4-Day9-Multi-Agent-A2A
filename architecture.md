# Multi-Agent E-commerce Dispute Resolution Architecture

## Luồng xử lý

```text
input/EC_xxx.json
        |
        v
Coordinator
        |
        v
DataRepository (read-only: data/*.csv)
        |
        +--> CustomerAgent ------> CustomerHandoff
        +--> OrderProductAgent --> OrderProductHandoff
        +--> PaymentAgent ------> PaymentHandoff
        +--> DeliveryAgent -----> DeliveryHandoff
                                        |
                                        v
                                  PolicyAgent
                                        |
                                        v
                                 PolicyDecision
                                        |
                                        v
                                   OutputVerifier
                                        |
                         +--------------+--------------+
                         v                             v
               output/EC_xxx.json          logging/trace.jsonl
                                             logging/metadata.json