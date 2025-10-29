#!/usr/bin/env python3
"""
Test database connections before running sync
"""

import sys
import pyodbc
import psycopg2
from sync_engine import SyncConfig, DatabaseConnector, logger


def test_sql_server():
    """Test connection to s002 SQL Server"""
    try:
        logger.info("Testing s002 SQL Server connection...")
        conn = DatabaseConnector.get_sql_server_connection(readonly=True)
        cursor = conn.cursor()

        # Test query
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()[0]
        logger.info(f"✅ SQL Server connected: {version[:50]}...")

        # Count records
        cursor.execute("SELECT COUNT(*) FROM tblFXTrade")
        fx_count = cursor.fetchone()[0]
        logger.info(f"✅ tblFXTrade records: {fx_count}")

        cursor.execute("SELECT COUNT(*) FROM tblFXOptionTrade")
        fxopt_count = cursor.fetchone()[0]
        logger.info(f"✅ tblFXOptionTrade records: {fxopt_count}")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        logger.error(f"❌ SQL Server connection failed: {e}")
        return False


def test_postgres():
    """Test connection to Azure PostgreSQL"""
    try:
        logger.info("Testing Azure PostgreSQL connection...")
        conn = DatabaseConnector.get_postgres_connection()
        cursor = conn.cursor()

        # Test query
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        logger.info(f"✅ PostgreSQL connected: {version[:50]}...")

        # Count records
        cursor.execute("SELECT COUNT(*) FROM gzc_fx_trade")
        fx_count = cursor.fetchone()[0]
        logger.info(f"✅ gzc_fx_trade records: {fx_count}")

        cursor.execute("SELECT COUNT(*) FROM gzc_fx_option_trade")
        fxopt_count = cursor.fetchone()[0]
        logger.info(f"✅ gzc_fx_option_trade records: {fxopt_count}")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        logger.error(f"❌ PostgreSQL connection failed: {e}")
        return False


if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("DATABASE CONNECTION TEST")
    logger.info("=" * 80)

    sql_ok = test_sql_server()
    print()
    pg_ok = test_postgres()

    print()
    logger.info("=" * 80)
    if sql_ok and pg_ok:
        logger.info("✅ ALL CONNECTIONS SUCCESSFUL")
        logger.info("=" * 80)
        sys.exit(0)
    else:
        logger.error("❌ SOME CONNECTIONS FAILED")
        logger.info("=" * 80)
        sys.exit(1)
