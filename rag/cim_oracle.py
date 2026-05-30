# rag/cim_oracle.py
import json
import chromadb
from chromadb.utils import embedding_functions

class CIMOracle:
    def __init__(self, json_path="rag/cim_subset.json", db_path="./chroma_db"):
        self.json_path = json_path
        
        # Initialize persistent local ChromaDB
        self.client = chromadb.PersistentClient(path=db_path)
        
        # Use a lightweight, fast, local embedding model
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        # Create or load the collection
        self.collection = self.client.get_or_create_collection(
            name="splunk_cim_fields",
            embedding_function=self.embedding_fn
        )
        
        # Auto-load data if collection is empty
        if self.collection.count() == 0:
            self._load_data()

    def _load_data(self):
        """Reads the CIM JSON and populates the vector database."""
        print("📚 Loading Splunk CIM schemas into Vector DB...")
        with open(self.json_path, "r") as f:
            cim_data = json.load(f)

        documents = []
        metadatas = []
        ids = []

        for model in cim_data:
            model_name = model["data_model"]
            for field in model["fields"]:
                cim_field = field["cim_field"]
                desc = field["description"]
                
                # The document is what we embed. We make it rich with context.
                doc = f"Data Model: {model_name}. Field: {cim_field}. Description: {desc}"
                documents.append(doc)
                
                # Metadata is returned upon a successful match
                metadatas.append({
                    "data_model": model_name,
                    "cim_field": cim_field,
                    "description": desc
                })
                ids.append(f"{model_name}_{cim_field}")

        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        print(f"✅ Loaded {len(documents)} CIM fields into ChromaDB.")

    def get_cim_mapping(self, extracted_field_name, context=""):
        """
        Queries the Vector DB to find the closest Splunk CIM standard field.
        """
        query_text = f"Find the Splunk CIM mapping for an extracted field named '{extracted_field_name}'. Context: {context}"
        
        results = self.collection.query(
            query_texts=[query_text],
            n_results=1
        )
        
        if results['metadatas'] and len(results['metadatas'][0]) > 0:
            best_match = results['metadatas'][0][0]
            return best_match
        return None