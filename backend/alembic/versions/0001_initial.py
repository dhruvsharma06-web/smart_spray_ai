"""initial schema
Revision ID: 0001_initial
Revises:
"""
from alembic import op
import sqlalchemy as sa
revision='0001_initial'; down_revision=None; branch_labels=None; depends_on=None

def upgrade():
    from app.models import User,Farm,Field,Device,SensorReading,CropRecord,AIAnalysis,DiseaseDetection,PestDetection,ClimateRisk,Decision,SprayEvent,Alert,Treatment,Feedback,AuditLog
    from app.database import Base
    bind=op.get_bind()
    Base.metadata.create_all(bind=bind)

def downgrade():
    from app.database import Base
    bind=op.get_bind(); Base.metadata.drop_all(bind=bind)
