/**
 * Jenkins Pipeline for S002 to Azure PostgreSQL Synchronization
 *
 * Designed for: Windows Jenkins Agent
 * Schedule: Every 15 minutes during trading hours
 *
 * Prerequisites:
 * - Python 3.8+ installed on Jenkins Windows agent
 * - ODBC Driver 18 for SQL Server installed
 * - Network access to s002 (S002.groundzero.local:1433) and Azure PostgreSQL
 */

pipeline {
    agent any 

    // Run every 15 minutes during trading hours (6 AM - 6 PM weekdays)
    triggers {
        cron('H/15 6-18 * * 1-5')
    }

    environment {
        // Source: S002 SQL Server (credentials from Jenkins)
        SQL_SERVER = 'S002.groundzero.local,1433'
        SQL_DATABASE = 'GZCDB'
        SQL_USERNAME = credentials('s002-sql-username')
        SQL_PASSWORD = credentials('s002-sql-password')

        // Target: Azure PostgreSQL (credentials from Jenkins)
        PG_HOST = 'gzcdevserver.postgres.database.azure.com'
        PG_DATABASE = 'gzc_platform'
        PG_USERNAME = credentials('azure-pg-username')
        PG_PASSWORD = credentials('azure-pg-password')

        // Sync options
        BATCH_SIZE = '1000'
        SYNC_CASH_TRANSACTIONS = 'false'  // Set to 'true' to sync cash transactions
    }

    options {
        // Keep last 30 builds
        buildDiscarder(logRotator(numToKeepStr: '30'))

        // Timeout after 10 minutes
        timeout(time: 10, unit: 'MINUTES')

        // Don't run concurrent syncs
        disableConcurrentBuilds()
    }

    stages {
        stage('Setup') {
            steps {
                echo 'Setting up Python environment...'
                bat '''
  C:\\BIN\\Python\\3.8\\python.exe --version
  C:\\BIN\\Python\\3.8\\python.exe -m pip install --upgrade pip setuptools wheel
  set PIP_PREFER_BINARY=1
  C:\\BIN\\Python\\3.8\\python.exe -m pip install --only-binary=:all: -r requirements.txt
'''
            }
        }

        stage('Sync FX Trades & Options') {
            steps {
                echo 'Starting synchronization from s002 to Azure PostgreSQL...'
                bat '''
                    python sync_engine.py
                '''
            }
        }
    }

    post {
        success {
            echo '✅ Sync completed successfully'
            // Archive sync log
            archiveArtifacts artifacts: 'sync.log', allowEmptyArchive: true
        }

        failure {
            echo '❌ Sync failed - check logs'
            // Archive sync log for debugging
            archiveArtifacts artifacts: 'sync.log', allowEmptyArchive: true

            // Send email notification (configure SMTP in Jenkins)
            emailext(
                subject: "S002 Sync Failed: ${env.JOB_NAME} - Build #${env.BUILD_NUMBER}",
                body: """
                    Sync from s002 to Azure PostgreSQL failed.

                    Job: ${env.JOB_NAME}
                    Build: ${env.BUILD_NUMBER}
                    Build URL: ${env.BUILD_URL}

                    Check the build logs for details.
                """,
                to: 'your-email@example.com',  // Update with your email
                attachLog: true
            )
        }

        always {
            echo 'Cleaning up workspace...'
            cleanWs(deleteDirs: true, patterns: [[pattern: '*.pyc', type: 'INCLUDE']])
        }
    }
}
