"""initial schema
Revision ID: 0001_initial
Revises:
Create Date: 2024-01-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='uq_users_email'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # farms
    op.create_table(
        'farms',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('location', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_farms_owner_id', 'farms', ['owner_id'])

    # fields
    op.create_table(
        'fields',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('farm_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('area_hectares', sa.Float(), nullable=True),
        sa.Column('crop', sa.String(100), nullable=True),
        sa.Column('growth_stage', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['farm_id'], ['farms.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_fields_farm_id', 'fields', ['farm_id'])

    # devices
    op.create_table(
        'devices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('field_id', sa.Integer(), nullable=False),
        sa.Column('device_uid', sa.String(100), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('device_type', sa.String(50), nullable=False, server_default='ESP32'),
        sa.Column('status', sa.String(30), nullable=False, server_default='OFFLINE'),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_command_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('tank_level', sa.Float(), nullable=True),
        sa.Column('pump_active', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['field_id'], ['fields.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('device_uid', name='uq_devices_device_uid'),
    )
    op.create_index('ix_devices_field_id', 'devices', ['field_id'])
    op.create_index('ix_devices_device_uid', 'devices', ['device_uid'], unique=True)

    # sensor_readings
    op.create_table(
        'sensor_readings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=False),
        sa.Column('device_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('server_timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('payload', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_sensor_readings_device_id', 'sensor_readings', ['device_id'])
    op.create_index('ix_sensor_readings_device_timestamp', 'sensor_readings', ['device_timestamp'])
    op.create_index('ix_sensor_readings_server_timestamp', 'sensor_readings', ['server_timestamp'])

    # crop_records
    op.create_table(
        'crop_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('field_id', sa.Integer(), nullable=False),
        sa.Column('crop', sa.String(100), nullable=False),
        sa.Column('growth_stage', sa.String(100), nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['field_id'], ['fields.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_crop_records_field_id', 'crop_records', ['field_id'])

    # ai_analyses
    op.create_table(
        'ai_analyses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('field_id', sa.Integer(), nullable=False),
        sa.Column('image_uri', sa.String(1000), nullable=True),
        sa.Column('crop', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('diagnosis', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('raw_result', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['field_id'], ['fields.id']),
    )
    op.create_index('ix_ai_analyses_field_id', 'ai_analyses', ['field_id'])

    # disease_detections
    op.create_table(
        'disease_detections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('analysis_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(150), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('severity', sa.String(30), nullable=True),
        sa.Column('affected_area_percent', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['analysis_id'], ['ai_analyses.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_disease_detections_analysis_id', 'disease_detections', ['analysis_id'])

    # pest_detections
    op.create_table(
        'pest_detections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('analysis_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(150), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('count', sa.Integer(), nullable=True),
        sa.Column('detections', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['analysis_id'], ['ai_analyses.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_pest_detections_analysis_id', 'pest_detections', ['analysis_id'])

    # climate_risk
    op.create_table(
        'climate_risk',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('analysis_id', sa.Integer(), nullable=False),
        sa.Column('drought', sa.Float(), nullable=False, server_default='0'),
        sa.Column('heat', sa.Float(), nullable=False, server_default='0'),
        sa.Column('flood', sa.Float(), nullable=False, server_default='0'),
        sa.Column('waterlogging', sa.Float(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['analysis_id'], ['ai_analyses.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_climate_risk_analysis_id', 'climate_risk', ['analysis_id'])

    # decisions
    op.create_table(
        'decisions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('field_id', sa.Integer(), nullable=False),
        sa.Column('analysis_id', sa.Integer(), nullable=True),
        sa.Column('primary_decision', sa.String(50), nullable=False),
        sa.Column('risk_level', sa.String(30), nullable=False),
        sa.Column('result', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['analysis_id'], ['ai_analyses.id']),
        sa.ForeignKeyConstraint(['field_id'], ['fields.id']),
    )
    op.create_index('ix_decisions_field_id', 'decisions', ['field_id'])
    op.create_index('ix_decisions_analysis_id', 'decisions', ['analysis_id'])

    # spray_events
    op.create_table(
        'spray_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=False),
        sa.Column('decision_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(30), nullable=False),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('idempotency_key', sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['decision_id'], ['decisions.id']),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id']),
        sa.UniqueConstraint('idempotency_key', name='uq_spray_events_idempotency_key'),
    )
    op.create_index('ix_spray_events_device_id', 'spray_events', ['device_id'])
    op.create_index('ix_spray_events_idempotency_key', 'spray_events', ['idempotency_key'], unique=True)

    # alerts
    op.create_table(
        'alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('field_id', sa.Integer(), nullable=False),
        sa.Column('alert_type', sa.String(60), nullable=False),
        sa.Column('severity', sa.String(30), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('acknowledged', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['field_id'], ['fields.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_alerts_field_id', 'alerts', ['field_id'])
    op.create_index('ix_alerts_alert_type', 'alerts', ['alert_type'])
    op.create_index('ix_alerts_created_at', 'alerts', ['created_at'])

    # treatments
    op.create_table(
        'treatments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('crop', sa.String(100), nullable=False),
        sa.Column('target', sa.String(150), nullable=False),
        sa.Column('product', sa.String(255), nullable=False),
        sa.Column('active_ingredient', sa.String(255), nullable=False),
        sa.Column('formulation', sa.String(100), nullable=True),
        sa.Column('application_method', sa.String(100), nullable=True),
        sa.Column('approved_crop', sa.String(100), nullable=False),
        sa.Column('approved_target', sa.String(150), nullable=False),
        sa.Column('label_rate', sa.String(255), nullable=True),
        sa.Column('pre_harvest_interval', sa.String(100), nullable=True),
        sa.Column('safety', sa.Text(), nullable=True),
        sa.Column('source', sa.String(1000), nullable=False),
        sa.Column('verification_date', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_treatments_crop', 'treatments', ['crop'])
    op.create_index('ix_treatments_target', 'treatments', ['target'])

    # feedback
    op.create_table(
        'feedback',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('field_id', sa.Integer(), nullable=False),
        sa.Column('analysis_id', sa.Integer(), nullable=True),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.Column('outcome', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['analysis_id'], ['ai_analyses.id']),
        sa.ForeignKeyConstraint(['field_id'], ['fields.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_feedback_field_id', 'feedback', ['field_id'])
    op.create_index('ix_feedback_analysis_id', 'feedback', ['analysis_id'])

    # audit_logs
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('entity_type', sa.String(100), nullable=True),
        sa.Column('entity_id', sa.String(100), nullable=True),
        sa.Column('metadata_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_logs_event_type', 'audit_logs', ['event_type'])
    op.create_index('ix_audit_logs_entity_type', 'audit_logs', ['entity_type'])
    op.create_index('ix_audit_logs_entity_id', 'audit_logs', ['entity_id'])


def downgrade():
    op.drop_table('audit_logs')
    op.drop_table('feedback')
    op.drop_table('treatments')
    op.drop_table('alerts')
    op.drop_table('spray_events')
    op.drop_table('decisions')
    op.drop_table('climate_risk')
    op.drop_table('pest_detections')
    op.drop_table('disease_detections')
    op.drop_table('ai_analyses')
    op.drop_table('crop_records')
    op.drop_table('sensor_readings')
    op.drop_table('devices')
    op.drop_table('fields')
    op.drop_table('farms')
    op.drop_table('users')