# S002 to Azure PostgreSQL Synchronization

**One-way synchronization** from s002 SQL Server (GZCDB) to Azure PostgreSQL (gzc_platform).

⚠️ **READ ONLY from s002** - This system NEVER writes back to s002.

## What It Syncs

| Source Table (s002) | Target Table (Azure) | Records |
|---------------------|---------------------|---------|
| `tblFXTrade` | `gzc_fx_trade` | ~2,885 |
| `tblFXOptionTrade` | `gzc_fx_option_trade` | ~449 |
| `tblCashTransaction` | `gzc_cash_transactions` | ~32,200 (optional) |

## Architecture

```
┌─────────────────────┐          ┌──────────────────────────┐
│   s002 SQL Server   │          │   Azure PostgreSQL       │
│   192.168.50.14     │  READ    │   gzcdevserver           │
│   GZCDB             │ ────────>│   gzc_platform           │
│   (READ ONLY)       │  ONLY    │   (WRITE)                │
└─────────────────────┘          └──────────────────────────┘
         │                                    ▲
         │                                    │
         └────────────────┬───────────────────┘
                          │
                    sync_engine.py
                  (Jenkins on Windows)
```

## Features

- ✅ **One-way sync only** - Never writes to s002
- ✅ **Incremental sync** - Only syncs new/missing records
- ✅ **Idempotent** - Safe to run multiple times
- ✅ **Exact matching** - Verifies all source records exist in target
- ✅ **Logging** - Detailed logs for troubleshooting
- ✅ **Jenkins ready** - Automated scheduling on Windows

## Prerequisites

### On Jenkins Windows Agent

1. **Python 3.8+**
   ```bash
   python --version
   ```

2. **ODBC Driver 18 for SQL Server**
   - Download: https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
   - Install on Windows Jenkins agent

3. **Network Access**
   - s002 SQL Server: `S002.groundzero.local:1433`
   - Azure PostgreSQL: `gzcdevserver.postgres.database.azure.com:5432`

## Installation

### Manual Setup (Windows)

```bash
# Clone repository
git clone https://github.com/GZCIM/s002-to-azure-sync.git
cd s002-to-azure-sync

# Install Python dependencies
pip install -r requirements.txt

# Configure credentials
copy .env.example .env
# Edit .env with your credentials

# Test sync
python sync_engine.py
```

### Jenkins Setup

1. **Create Jenkins Credentials**
   - Go to Jenkins → Credentials → System → Global credentials
   - Add credentials:
     - ID: `s002-sql-username`, Value: `production`
     - ID: `s002-sql-password`, Value: `<password>`
     - ID: `azure-pg-username`, Value: `mikael`
     - ID: `azure-pg-password`, Value: `<password>`

2. **Create Jenkins Pipeline**
   - New Item → Pipeline
   - Name: `s002-to-azure-sync`
   - Pipeline definition: Pipeline script from SCM
   - SCM: Git
   - Repository URL: `https://github.com/GZCIM/s002-to-azure-sync.git`
   - Script Path: `Jenkinsfile`

3. **Configure Schedule** (optional)
   - Edit `Jenkinsfile` cron trigger
   - Default: Every 15 minutes during trading hours (6 AM - 6 PM weekdays)
   ```groovy
   triggers {
       cron('H/15 6-18 * * 1-5')
   }
   ```

## Usage

### Run Manually

```bash
python sync_engine.py
```

### Run with Custom Settings

```bash
# Windows
set BATCH_SIZE=2000
set SYNC_CASH_TRANSACTIONS=true
python sync_engine.py

# Linux/Mac
export BATCH_SIZE=2000
export SYNC_CASH_TRANSACTIONS=true
python sync_engine.py
```

### Run in Jenkins

1. Go to Jenkins job: `s002-to-azure-sync`
2. Click "Build Now"
3. Monitor console output
4. Check `sync.log` artifact for details

## Configuration

All configuration via environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `SQL_SERVER` | `S002.groundzero.local,1433` | s002 SQL Server host |
| `SQL_DATABASE` | `GZCDB` | Source database name |
| `SQL_USERNAME` | `production` | SQL Server username |
| `SQL_PASSWORD` | - | SQL Server password |
| `PG_HOST` | `gzcdevserver.postgres.database.azure.com` | Azure PostgreSQL host |
| `PG_DATABASE` | `gzc_platform` | Target database name |
| `PG_USERNAME` | `mikael` | PostgreSQL username |
| `PG_PASSWORD` | - | PostgreSQL password |
| `BATCH_SIZE` | `1000` | Insert batch size |
| `SYNC_CASH_TRANSACTIONS` | `false` | Sync cash transactions (32K records) |

## How It Works

1. **Connect** to both databases (s002 READ ONLY, Azure WRITE)
2. **Compare** trade IDs between source and target
3. **Identify** missing records in Azure
4. **Fetch** missing records from s002
5. **Insert** missing records into Azure (batch insert)
6. **Verify** final counts match
7. **Log** results and close connections

## Sync Logic

```python
# For each table:
source_ids = get_all_trade_ids_from_s002()
target_ids = get_all_trade_ids_from_azure()

missing_ids = source_ids - target_ids

if missing_ids:
    records = fetch_records_from_s002(missing_ids)
    insert_into_azure(records)

verify_exact_match()
```

## Monitoring

### Logs

- Console output: Real-time sync progress
- `sync.log`: Detailed log file (archived by Jenkins)

### Success Criteria

```
✅ EXACT MATCH - All records synced!
```

### Warning Signs

```
⚠️  MISMATCH - Expected X, got Y
```

## Troubleshooting

### Connection Issues

**Error: `Connection refused to s002`**
- Check network connectivity: `ping 192.168.50.14`
- Verify SQL Server port: `telnet 192.168.50.14 1433`
- Check firewall rules

**Error: `ODBC Driver not found`**
- Install ODBC Driver 18 for SQL Server on Windows
- Verify driver name: `{ODBC Driver 18 for SQL Server}`

### Authentication Issues

**Error: `Login failed for user 'production'`**
- Verify credentials in `.env` or Jenkins credentials
- Check SQL Server user permissions

**Error: `password authentication failed for user "mikael"`**
- Verify Azure PostgreSQL credentials
- Check firewall rules allow Jenkins IP

### Data Issues

**Warning: `MISMATCH`**
- Check sync.log for detailed error messages
- Verify network connectivity during sync
- Check database locks or long-running transactions

## Security

⚠️ **NEVER commit credentials to Git!**

- ✅ Use `.env` file (gitignored)
- ✅ Use Jenkins credentials store
- ✅ Use environment variables
- ❌ Never hardcode passwords in code

## Maintenance

### Update Credentials

**In Jenkins:**
1. Jenkins → Credentials → Update credential value
2. No code changes needed

**For local runs:**
1. Edit `.env` file
2. Restart sync

### Change Sync Schedule

Edit `Jenkinsfile`:
```groovy
triggers {
    cron('H/30 * * * *')  // Every 30 minutes
}
```

### Add New Tables

Edit `sync_engine.py`:
1. Create new sync class (copy `FXTradeSync` pattern)
2. Add to `main()` function
3. Test thoroughly before deploying

## Support

- **Repository**: https://github.com/GZCIM/s002-to-azure-sync
- **Issues**: https://github.com/GZCIM/s002-to-azure-sync/issues

## License

Internal use only - GZCIM organization

---

**Last Updated**: 2025-10-29
**Version**: 1.0.0
