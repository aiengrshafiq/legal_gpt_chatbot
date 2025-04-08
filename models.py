from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from db import Base

class CaseLog(Base):
    __tablename__ = "case_logs"
    id = Column(Integer, primary_key=True, index=True)
    case_title = Column(String)
    case_text = Column(Text)
    advice = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class PDFDocument(Base):
    __tablename__ = "pdf_documents"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    source = Column(String)
    tags = Column(String)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
