from django.core.management.base import BaseCommand
from core.tasks import ingest_customers, ingest_loans


class Command(BaseCommand):
    help = 'Ingest customer and loan data from Excel files'

    def handle(self, *args, **options):
        self.stdout.write('Ingesting customers...')
        result = ingest_customers()
        self.stdout.write(self.style.SUCCESS(result))
        
        self.stdout.write('Ingesting loans...')
        result = ingest_loans()
        self.stdout.write(self.style.SUCCESS(result))
