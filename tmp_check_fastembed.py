from fastembed import TextEmbedding
models = TextEmbedding.list_supported_models()
bge = [m for m in models if 'bge' in m['model'].lower()]
for m in bge:
    print(f"{m['model']}: dim={m['dim']}")
