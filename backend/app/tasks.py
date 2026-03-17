from app.celery_worker import celery_app
from app import utils, rag, database, models
from sqlalchemy.orm import Session

# This decorator makes it a background task
@celery_app.task(name="process_document_task")
def process_document_task(doc_id: int, file_path: str):
    print(f"🚀 Worker starting processing for Doc ID: {doc_id}")
    
    # 1. Extract Text (Heavy IO)
    extracted_text = utils.get_pdf_text(file_path)
    
    if not extracted_text.strip():
        print("⚠️ No text found in PDF.")
        return

    # 2. Add to Vector DB (Heavy AI processing)
    # Note: We query DB to get the title for metadata if needed, 
    # but for speed we can just pass minimal metadata here.
    rag.add_text_to_vector_store(
        text=extracted_text, 
        metadata={"doc_id": doc_id}
    )

    # 3. Update SQL Database (Optional but recommended)
    # We open a NEW session because this is running in a separate process
    db: Session = database.SessionLocal()
    try:
        doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
        if doc:
            doc.content = extracted_text
            db.commit()
            print("✅ Database updated with extracted content.")
    except Exception as e:
        print(f"❌ Error updating DB: {e}")
    finally:
        db.close()
        
    print(f"🏁 Worker finished processing Doc ID: {doc_id}")