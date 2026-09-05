from FlagEmbedding import FlagModel

model = FlagModel(
    "BAAI/bge-small-en-v1.5",
    use_fp16=False,
)

emb = model.encode(["Hello world"])

print(type(emb))
print(len(emb))
print(len(emb[0]))