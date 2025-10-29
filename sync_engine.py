#!/usr/bin/env python3
"""
S002 to Azure PostgreSQL Synchronization Engine

ONE-WAY SYNC ONLY: Reads from s002 SQL Server, writes to Azure PostgreSQL
NEVER writes back to s002

Syncs:
- tblFXTrade -> gzc_fx_trade
- tblFXOptionTrade -> gzc_fx_option_trade
- tblCashTransaction -> gzc_cash_transactions (optional)

Designed for Jenkins CI/CD on Windows
"""

import os
import sys
import logging
from datetime import datetime
from typing import Dict, Set, Tuple
import pyodbc
import psycopg2
from psycopg2.extras import execute_batch

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('sync.log')
    ]
)
logger = logging.getLogger(__name__)


class SyncConfig:
    """Configuration from environment variables or defaults"""

    # S002 SQL Server (READ ONLY)
    SQL_SERVER = os.getenv('SQL_SERVER', '192.168.50.14')
    SQL_DATABASE = os.getenv('SQL_DATABASE', 'GZCDB')
    SQL_USERNAME = os.getenv('SQL_USERNAME', 'production')
    SQL_PASSWORD = os.getenv('SQL_PASSWORD', 'pq12rs34')
    SQL_DRIVER = os.getenv('SQL_DRIVER', '{ODBC Driver 18 for SQL Server}')

    # Azure PostgreSQL (WRITE)
    PG_HOST = os.getenv('PG_HOST', 'gzcdevserver.postgres.database.azure.com')
    PG_DATABASE = os.getenv('PG_DATABASE', 'gzc_platform')
    PG_USERNAME = os.getenv('PG_USERNAME', 'mikael')
    PG_PASSWORD = os.getenv('PG_PASSWORD', 'Ii89rra137+*')
    PG_SSLMODE = os.getenv('PG_SSLMODE', 'require')

    # Sync options
    BATCH_SIZE = int(os.getenv('BATCH_SIZE', '1000'))
    SYNC_CASH_TRANSACTIONS = os.getenv('SYNC_CASH_TRANSACTIONS', 'false').lower() == 'true'


class DatabaseConnector:
    """Handles database connections"""

    @staticmethod
    def get_sql_server_connection(readonly: bool = True):
        """Get connection to s002 SQL Server (READ ONLY by default)"""
        conn_str = (
            f"DRIVER={SyncConfig.SQL_DRIVER};"
            f"SERVER={SyncConfig.SQL_SERVER};"
            f"DATABASE={SyncConfig.SQL_DATABASE};"
            f"UID={SyncConfig.SQL_USERNAME};"
            f"PWD={SyncConfig.SQL_PASSWORD};"
            f"TrustServerCertificate=yes;"
        )

        conn = pyodbc.connect(conn_str, readonly=readonly)
        logger.info(f"Connected to SQL Server: {SyncConfig.SQL_SERVER}/{SyncConfig.SQL_DATABASE} (readonly={readonly})")
        return conn

    @staticmethod
    def get_postgres_connection():
        """Get connection to Azure PostgreSQL"""
        conn = psycopg2.connect(
            host=SyncConfig.PG_HOST,
            database=SyncConfig.PG_DATABASE,
            user=SyncConfig.PG_USERNAME,
            password=SyncConfig.PG_PASSWORD,
            sslmode=SyncConfig.PG_SSLMODE
        )
        logger.info(f"Connected to PostgreSQL: {SyncConfig.PG_HOST}/{SyncConfig.PG_DATABASE}")
        return conn


class FXTradeSync:
    """Sync FX spot/forward trades"""

    SOURCE_TABLE = "tblFXTrade"
    TARGET_TABLE = "gzc_fx_trade"

    @staticmethod
    def get_source_ids(cursor) -> Set[int]:
        """Get all trade IDs from s002"""
        cursor.execute(f"SELECT TradeId FROM {FXTradeSync.SOURCE_TABLE}")
        return set(row[0] for row in cursor.fetchall())

    @staticmethod
    def get_target_ids(cursor) -> Set[int]:
        """Get all trade IDs from Azure"""
        cursor.execute(f"SELECT trade_id FROM {FXTradeSync.TARGET_TABLE}")
        return set(row[0] for row in cursor.fetchall())

    @staticmethod
    def fetch_missing_records(cursor, missing_ids: Set[int]) -> list:
        """Fetch full records for missing IDs from s002"""
        if not missing_ids:
            return []

        placeholders = ','.join('?' * len(missing_ids))
        query = f"""
            SELECT
                TradeId, ExternalTradeId, TradeDate, MaturityDate, EffectiveDate,
                Quantity, Price, TradeCurrency, SettlementCurrency, Position,
                CounterPartyCode, GiveUpCounterPartyCode, NDF, StrategyFolderId,
                Note, Active, FundId, Trader, DecisionTimestamp, Location,
                IsValidated, Validator, ModUser, ModTimestamp
            FROM {FXTradeSync.SOURCE_TABLE}
            WHERE TradeId IN ({placeholders})
            ORDER BY TradeId
        """

        cursor.execute(query, tuple(missing_ids))
        return cursor.fetchall()

    @staticmethod
    def insert_records(cursor, records: list):
        """Insert records into Azure PostgreSQL"""
        if not records:
            return 0

        insert_query = f"""
            INSERT INTO {FXTradeSync.TARGET_TABLE} (
                trade_id, external_trade_id, trade_date, maturity_date, effective_date,
                quantity, price, trade_currency, settlement_currency, position,
                counter_party_code, give_up_counter_party_code, ndf, strategy_folder_id,
                note, active, fund_id, trader, decision_timestamp, location,
                is_validated, validator, mod_user, mod_timestamp
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            ON CONFLICT (trade_id) DO NOTHING
        """

        execute_batch(cursor, insert_query, records, page_size=SyncConfig.BATCH_SIZE)
        return len(records)

    @staticmethod
    def sync():
        """Execute FX trade sync"""
        logger.info("=" * 80)
        logger.info("SYNCING FX TRADES")
        logger.info("=" * 80)

        sql_conn = DatabaseConnector.get_sql_server_connection(readonly=True)
        sql_cursor = sql_conn.cursor()

        pg_conn = DatabaseConnector.get_postgres_connection()
        pg_cursor = pg_conn.cursor()

        try:
            # Get IDs from both systems
            source_ids = FXTradeSync.get_source_ids(sql_cursor)
            target_ids = FXTradeSync.get_target_ids(pg_cursor)

            logger.info(f"Source (s002): {len(source_ids)} records")
            logger.info(f"Target (Azure): {len(target_ids)} records")

            # Find missing records
            missing_ids = source_ids - target_ids
            logger.info(f"Missing in Azure: {len(missing_ids)} records")

            if missing_ids:
                # Fetch and insert missing records
                records = FXTradeSync.fetch_missing_records(sql_cursor, missing_ids)
                inserted = FXTradeSync.insert_records(pg_cursor, records)
                pg_conn.commit()
                logger.info(f"✅ Inserted {inserted} records")

            # Final verification
            pg_cursor.execute(f"SELECT COUNT(*) FROM {FXTradeSync.TARGET_TABLE}")
            final_count = pg_cursor.fetchone()[0]
            logger.info(f"✅ Final count in Azure: {final_count}")

            if final_count == len(source_ids):
                logger.info("✅ EXACT MATCH - All records synced!")
                return True
            else:
                logger.warning(f"⚠️  MISMATCH - Expected {len(source_ids)}, got {final_count}")
                return False

        finally:
            sql_cursor.close()
            sql_conn.close()
            pg_cursor.close()
            pg_conn.close()


class FXOptionTradeSync:
    """Sync FX option trades"""

    SOURCE_TABLE = "tblFXOptionTrade"
    TARGET_TABLE = "gzc_fx_option_trade"

    @staticmethod
    def get_source_ids(cursor) -> Set[int]:
        """Get all trade IDs from s002"""
        cursor.execute(f"SELECT TradeId FROM {FXOptionTradeSync.SOURCE_TABLE}")
        return set(row[0] for row in cursor.fetchall())

    @staticmethod
    def get_target_ids(cursor) -> Set[int]:
        """Get all trade IDs from Azure"""
        cursor.execute(f"SELECT trade_id FROM {FXOptionTradeSync.TARGET_TABLE}")
        return set(row[0] for row in cursor.fetchall())

    @staticmethod
    def fetch_missing_records(cursor, missing_ids: Set[int]) -> list:
        """Fetch full records for missing IDs from s002"""
        if not missing_ids:
            return []

        placeholders = ','.join('?' * len(missing_ids))
        query = f"""
            SELECT
                TradeId, ExternalTradeId, TradeDate, MaturityDate, EffectiveDate,
                PremiumPaymentDate, UnderlyingTradeCurrency, UnderlyingSettlementCurrency,
                Strike, Quantity, Premium, CashAmount, Position, StrikeCurrency,
                SettlementCurrency, OptionStyle, OptionType, Cut, isCashSettled,
                CounterPartyCode, GiveUpCounterPartyCode, StrategyFolderId, Active,
                FundId, Note, Trader, DecisionTimestamp, Location, IsValidated,
                Validator, ModUser, ModTimestamp
            FROM {FXOptionTradeSync.SOURCE_TABLE}
            WHERE TradeId IN ({placeholders})
            ORDER BY TradeId
        """

        cursor.execute(query, tuple(missing_ids))
        return cursor.fetchall()

    @staticmethod
    def insert_records(cursor, records: list):
        """Insert records into Azure PostgreSQL"""
        if not records:
            return 0

        insert_query = f"""
            INSERT INTO {FXOptionTradeSync.TARGET_TABLE} (
                trade_id, external_trade_id, trade_date, maturity_date, effective_date,
                premium_payment_date, underlying_trade_currency, underlying_settlement_currency,
                strike, quantity, premium, cash_amount, position, strike_currency,
                settlement_currency, option_style, option_type, cut, is_cash_settled,
                counter_party_code, give_up_counter_party_code, strategy_folder_id, active,
                fund_id, note, trader, decision_timestamp, location, is_validated,
                validator, mod_user, mod_timestamp
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s
            )
            ON CONFLICT (trade_id) DO NOTHING
        """

        execute_batch(cursor, insert_query, records, page_size=SyncConfig.BATCH_SIZE)
        return len(records)

    @staticmethod
    def sync():
        """Execute FX option trade sync"""
        logger.info("=" * 80)
        logger.info("SYNCING FX OPTION TRADES")
        logger.info("=" * 80)

        sql_conn = DatabaseConnector.get_sql_server_connection(readonly=True)
        sql_cursor = sql_conn.cursor()

        pg_conn = DatabaseConnector.get_postgres_connection()
        pg_cursor = pg_conn.cursor()

        try:
            # Get IDs from both systems
            source_ids = FXOptionTradeSync.get_source_ids(sql_cursor)
            target_ids = FXOptionTradeSync.get_target_ids(pg_cursor)

            logger.info(f"Source (s002): {len(source_ids)} records")
            logger.info(f"Target (Azure): {len(target_ids)} records")

            # Find missing records
            missing_ids = source_ids - target_ids
            logger.info(f"Missing in Azure: {len(missing_ids)} records")

            if missing_ids:
                # Fetch and insert missing records
                records = FXOptionTradeSync.fetch_missing_records(sql_cursor, missing_ids)
                inserted = FXOptionTradeSync.insert_records(pg_cursor, records)
                pg_conn.commit()
                logger.info(f"✅ Inserted {inserted} records")

            # Final verification
            pg_cursor.execute(f"SELECT COUNT(*) FROM {FXOptionTradeSync.TARGET_TABLE}")
            final_count = pg_cursor.fetchone()[0]
            logger.info(f"✅ Final count in Azure: {final_count}")

            if final_count == len(source_ids):
                logger.info("✅ EXACT MATCH - All records synced!")
                return True
            else:
                logger.warning(f"⚠️  MISMATCH - Expected {len(source_ids)}, got {final_count}")
                return False

        finally:
            sql_cursor.close()
            sql_conn.close()
            pg_cursor.close()
            pg_conn.close()


def main():
    """Main sync orchestrator"""
    logger.info("=" * 80)
    logger.info("S002 TO AZURE POSTGRESQL SYNCHRONIZATION")
    logger.info("ONE-WAY SYNC: s002 (READ ONLY) → Azure PostgreSQL (WRITE)")
    logger.info("=" * 80)
    logger.info(f"Started at: {datetime.now()}")
    logger.info("")

    success = True

    try:
        # Sync FX trades
        if not FXTradeSync.sync():
            success = False

        logger.info("")

        # Sync FX option trades
        if not FXOptionTradeSync.sync():
            success = False

        logger.info("")
        logger.info("=" * 80)
        if success:
            logger.info("✅ ALL SYNCS COMPLETED SUCCESSFULLY")
        else:
            logger.warning("⚠️  SYNC COMPLETED WITH WARNINGS")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ SYNC FAILED: {e}", exc_info=True)
        sys.exit(1)

    logger.info(f"Completed at: {datetime.now()}")

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
