import sqlite3
import psycopg2
from sqlalchemy import create_engine, MetaData, Table, select
from sqlalchemy.orm import sessionmaker
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
SQLITE_DB = "growth_flywheel.db"
POSTGRES_URL = "postgresql://growth_user:password@localhost:5432/growth_flywheel"

def migrate_data():
    """Migrate data from SQLite to PostgreSQL while respecting schema."""
    logger.info(f"Starting migration from {SQLITE_DB} to PostgreSQL...")
    
    # Create engines
    sqlite_engine = create_engine(f"sqlite:///{SQLITE_DB}")
    pg_engine = create_engine(POSTGRES_URL)
    
    # Reflect tables
    metadata = MetaData()
    metadata.reflect(bind=sqlite_engine)
    
    # Migration order to respect foreign keys (simplified)
    # 1. Main tables
    # 2. Detail tables
    table_order = [
        'xhs_notes', 'patterns', 'generations', 'grpo_runs', 'crawl_tasks',
        'xhs_metrics', 'xhs_covers', 'xhs_analysis', 'pattern_samples', 'online_metrics'
    ]
    
    for table_name in table_order:
        if table_name not in metadata.tables:
            logger.warning(f"Table {table_name} not found in SQLite, skipping...")
            continue
            
        logger.info(f"Migrating table: {table_name}")
        table = metadata.tables[table_name]
        
        # Read data from SQLite
        with sqlite_engine.connect() as sqlite_conn:
            data = sqlite_conn.execute(select(table)).fetchall()
            
        if not data:
            logger.info(f"No data for {table_name}, skipping...")
            continue
            
        # Write to PostgreSQL
        with pg_engine.connect() as pg_conn:
            # Use multi-row insert for efficiency if needed, but for small-medium data this is safer
            for row in data:
                try:
                    pg_conn.execute(table.insert().values(**dict(row._mapping)))
                except Exception as e:
                    logger.error(f"Error inserting row into {table_name}: {e}")
            pg_conn.commit()
            
    logger.info("Migration completed successfully!")

if __name__ == "__main__":
    try:
        migrate_data()
    except Exception as e:
        logger.error(f"Migration failed: {e}")
