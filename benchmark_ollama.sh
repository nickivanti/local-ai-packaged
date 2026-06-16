#!/bin/bash
echo "=== Ollama Performance Benchmark ==="
echo "Model: llama3.1 (4.9GB)"
echo "GPU: NVIDIA T1200 Laptop GPU (4GB VRAM)"
echo ""

PROMPT="Explain the theory of relativity, including both special and general relativity, with mathematical formulas and real-world applications."

echo "Running benchmark..."
time docker exec ollama ollama run llama3.1 "$PROMPT" --verbose 2>&1 | tee benchmark_result.txt

echo ""
echo "=== Results ==="
grep -E "total duration|eval duration|eval count|prompt eval count" benchmark_result.txt
