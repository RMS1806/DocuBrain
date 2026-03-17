from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from app import database, models, schemas, dependencies
from app.tasks import process_document_task # Import the task
import os
import shutil

router = APIRouter(tags=["Documents"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload", response_model=schemas.DocumentResponse)
def upload_document(
    file: UploadFile = File(...), 
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(database.get_db)
):
    if file.content_type != "application/pdf":
        raise HTTPException(400, detail="Only PDF files are allowed")

    # 1. Save file to disk
    file_location = f"{UPLOAD_DIR}/{file.filename}"
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 2. Create DB Entry (Metadata only, no content yet)
    new_doc = models.Document(
        title=file.filename,
        file_path=file_location,
        content="Processing...", # Placeholder text
        user_id=current_user.id
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)

    # 3. 🚀 Send task to Redis (Background Work)
    # usage: task_name.delay(arguments)
    process_document_task.delay(new_doc.id, file_location)
    
    return new_doc

# ... keep GET endpoints the same ...

# ... keep existing imports ...

# 👇 Add this new endpoint to LIST documents
@router.get("/documents", response_model=list[schemas.DocumentResponse])
def get_my_documents(
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(database.get_db)
):
    # Return all documents belonging to the user
    return current_user.documents

# 👇 Add this new endpoint to READ a specific document
@router.get("/documents/{doc_id}", response_model=schemas.DocumentDetail)
def get_document_content(
    doc_id: int,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(database.get_db)
):
    # Find the document
    doc = db.query(models.Document).filter(
        models.Document.id == doc_id, 
        models.Document.user_id == current_user.id
    ).first()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    return doc