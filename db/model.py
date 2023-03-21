from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, TEXT, Date, Boolean, INTEGER, DateTime, Table
from sqlalchemy.sql.schema import ForeignKey
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, relationship
from db.config import ASYNC_SQLALCHEMY_DATABASE_URI

engine = create_async_engine(ASYNC_SQLALCHEMY_DATABASE_URI, future=True)
"""
expire_on_commit=False makes sure that our db entities and fields 
will be available even after a commit was made on the session, 
and class_=AsyncSession is the new async session. 
"""
Session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()

StudyPatient = Table(
    "StudyPatient",
    Base.metadata,
    Column("study_id", ForeignKey("Study.id"), primary_key=True),
    Column("patient_id", ForeignKey("Patient.id"), primary_key=True),
)

PatientWSI = Table(
    "PatientWSI",
    Base.metadata,
    Column("patient_id", ForeignKey("Patient.id"), primary_key=True),
    Column("wsi_id", ForeignKey("WSI.id"), primary_key=True, unique=True),
)

CaseWSI = Table(
    "CaseWSI",
    Base.metadata,
    Column("case_id", ForeignKey("Case.id"), primary_key=True),
    Column("wsi_id", ForeignKey("WSI.id"), primary_key=True),
)


class Study(Base):
    __tablename__ = "Study"
    id = Column(String(255), primary_key=True)
    name = Column(TEXT, nullable=True)
    date = Column(Date, nullable=True)
    pseudo_id = Column(String(255), unique=True, nullable=False)
    pseudo_name = Column(TEXT, nullable=True)
    pseudo_date = Column(Date, nullable=True)
    patients = relationship('model.Patient', secondary=StudyPatient, backref='studies')


class Patient(Base):
    __tablename__ = "Patient"
    id = Column(String(255), primary_key=True)
    name = Column(TEXT, nullable=True)
    sex = Column(INTEGER, nullable=True)
    age = Column(INTEGER, nullable=True)
    pseudo_id = Column(String(255), unique=True, nullable=False)
    pseudo_name = Column(TEXT, nullable=True)
    pseudo_age = Column(INTEGER, nullable=True)
    slides = relationship('model.WSI', secondary=PatientWSI, back_populates='patients')


class Case(Base):
    __tablename__ = "Case"
    id = Column(String(255), primary_key=True)
    name = Column(TEXT, nullable=True)
    created_at = Column(DateTime, nullable=True)
    pseudo_id = Column(String(255), unique=True, nullable=False)
    pseudo_name = Column(TEXT, nullable=True)
    pseudo_created_at = Column(DateTime, nullable=True)
    slides = relationship('model.WSI', secondary=CaseWSI, back_populates='cases')


class WSI(Base):
    __tablename__ = "WSI"
    id = Column(String(255), primary_key=True)
    name = Column(TEXT, nullable=True)
    acquired_at = Column(DateTime, nullable=True)
    stain = Column(TEXT, nullable=True)
    tissue = Column(TEXT, nullable=True)
    pseudo_id = Column(String(255), unique=True, nullable=False)
    pseudo_name = Column(TEXT, nullable=True)
    pseudo_acquired_at = Column(DateTime, nullable=True)
    pseudo_label_name = Column(TEXT, nullable=True)
    pseudo_label_key = Column(TEXT, nullable=True)
    pseudo_macro_name = Column(TEXT, nullable=True)
    pseudo_macro_key = Column(TEXT, nullable=True)
    pseudo_metadata_name = Column(TEXT, nullable=True)
    pseudo_metadata_key = Column(TEXT, nullable=True)
    cases = relationship('model.Case', secondary=CaseWSI, back_populates='slides')
    patients = relationship('model.Patient', secondary=PatientWSI, back_populates='slides')


