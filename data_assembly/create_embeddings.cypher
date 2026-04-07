CREATE VECTOR INDEX survivor_embeddings IF NOT EXISTS
FOR (s:Survivor) ON (s.embedding)
OPTIONS {indexConfig: {
 `vector.dimensions`: 768,
 `vector.similarity_function`: 'cosine'
}};