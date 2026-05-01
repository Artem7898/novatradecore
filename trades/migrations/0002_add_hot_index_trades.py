from django.db import migrations


class Migration(migrations.Migration):
    # ВАЖНО: atomic = False обязательно для CONCURRENTLY
    atomic = False

    dependencies = [
        ('trades', '0001_initial'),
    ]


    def upgrade(self, apps, schema_editor) -> None:
        if schema_editor.connection.vendor != 'postgresql':
            return

        with schema_editor.connection.cursor() as cursor:
            cursor.execute("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_symbol_created 
                ON trades_trade (symbol, created_at DESC NULLS LAST);
            """)
            cursor.execute("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_exchange_id 
                ON trades_trade (exchange_id);
            """)


    def downgrade(self, apps, schema_editor) -> None:
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_trades_symbol_created;")
            cursor.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_trades_exchange_id;")