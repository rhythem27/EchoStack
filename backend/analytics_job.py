import os
import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit, current_timestamp

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend-analytics-job")

def run_analytics_etl():
    # Retrieve configurations from environment
    db_host = os.getenv("POSTGRES_HOST", "postgres")
    db_port = os.getenv("POSTGRES_PORT", "5432")
    db_name = os.getenv("POSTGRES_DB", "echostack_db")
    db_user = os.getenv("POSTGRES_USER", "postgres_user")
    db_pass = os.getenv("POSTGRES_PASSWORD", "postgres_secure_password")
    spark_master = os.getenv("SPARK_MASTER_URL", "local[*]")

    # PostgreSQL JDBC Connection String
    # Critically append ?stringtype=unspecified to allow Postgres to automatically cast strings into UUID / JSONB types
    jdbc_url = f"jdbc:postgresql://{db_host}:{db_port}/{db_name}?stringtype=unspecified"

    logger.info("Initializing resource-constrained SparkSession...")
    # Configure Spark Session to run within strict 800MB RAM memory allocations
    spark = SparkSession.builder \
        .appName("EchoStackTelemetryETL") \
        .master(spark_master) \
        .config("spark.executor.memory", "800m") \
        .config("spark.driver.memory", "800m") \
        .config("spark.sql.shuffle.partitions", "4") \
        .getOrCreate()

    try:
        logger.info("Reading telemetry data from chat_logs table via JDBC...")
        # Configure JDBC Partitioning to read in parallel safely (max 4 partitions, fetchsize 5000)
        df_chat_logs = spark.read \
            .format("jdbc") \
            .option("url", jdbc_url) \
            .option("dbtable", "chat_logs") \
            .option("user", db_user) \
            .option("password", db_pass) \
            .option("driver", "org.postgresql.Driver") \
            .option("partitionColumn", "id") \
            .option("lowerBound", "1") \
            .option("upperBound", "100000") \
            .option("numPartitions", "4") \
            .option("fetchsize", "5000") \
            .load()

        logger.info("Aggregating interactions count per user...")
        # Mock Transformation: Compute total interactions grouped by user_id
        df_aggregated = df_chat_logs.groupBy("user_id") \
            .count() \
            .withColumnRenamed("count", "total_interactions") \
            .withColumn("top_topics", lit('["general", "ai_architecture"]')) \
            .withColumn("last_updated_at", current_timestamp())

        logger.info("Writing aggregates to user_analytics table...")
        # Write back using mode("overwrite") + truncate to preserve table constraints and references
        df_aggregated.write \
            .format("jdbc") \
            .option("url", jdbc_url) \
            .option("dbtable", "user_analytics") \
            .option("user", db_user) \
            .option("password", db_pass) \
            .option("driver", "org.postgresql.Driver") \
            .option("truncate", "true") \
            .mode("overwrite") \
            .save()

        logger.info("PySpark Telemetry Aggregation ETL completed successfully.")
        
    except Exception as e:
        logger.error(f"PySpark ETL job failed: {e}")
        raise
    finally:
        spark.stop()

if __name__ == "__main__":
    run_analytics_etl()
