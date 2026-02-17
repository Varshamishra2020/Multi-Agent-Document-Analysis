# System Architecture Overview

## Multi-Agent Design
The system employs a delegated reasoning pattern. The **Manager Agent** handles the high-level orchestration, security, and tool-triggering logic, while the **Specialist Agent** focuses exclusively on data synthesis and grounding.

## Knowledge Retrieval (MCP)
The search engine uses a weighted scoring algorithm that considers:
- Term frequency (TF)
- Phrase matching bonus
- Snippet relevance ranking

## Reliability & Scalability
- **Dead-letter Queues:** Used in the data pipeline to handle malformed records.
- **Quantization:** 4-bit weights enable deployment on consumer-grade hardware without losing significant accuracy.
- **K8s Integration:** Planned for Q1 2026 to allow full auto-scaling of processing nodes.

## Security
All tool calls are authenticated via the MCP v1 protocol, ensuring that agents only access documents they are authorized to see.
