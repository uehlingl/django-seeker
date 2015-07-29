from django.conf import settings
from django.core.management.base import BaseCommand
from elasticsearch.helpers import bulk
from elasticsearch_dsl.connections import connections
from seeker.registry import documents, app_documents
from seeker.utils import progress
import gc

def reindex(doc_class, index, using, options):
    """
    Index all the things, using ElasticSearch's bulk API for speed.
    """
    def get_actions():
        for doc in doc_class.documents():
            action = {
                '_index': index,
                '_type': doc_class._doc_type.name,
            }
            action.update(doc)
            yield action
    es = connections.get_connection(using)
    actions = get_actions() if options['quiet'] else progress(get_actions(), count=doc_class.count(), label=doc_class.__name__)
    bulk(es, actions)
    es.indices.refresh(index=index)

class Command (BaseCommand):
    args = '<app1 app2 ...>'
    help = 'Re-indexes the specified applications'

    def add_arguments(self, parser):
        parser.add_argument('--using',
            dest='using',
            default=None,
            help='The ES connection alias to use'
        )
        parser.add_argument('--index',
            dest='index',
            default=None,
            help='The ES index to store data in'
        )
        parser.add_argument('--quiet',
            action='store_true',
            dest='quiet',
            default=False,
            help='Do not produce any output while indexing')
        parser.add_argument('--keep',
            action='store_true',
            dest='keep',
            default=False,
            help='Keep the existing mapping, instead of re-creating it'
        )
        parser.add_argument('--no-data',
            action='store_false',
            dest='data',
            default=True,
            help='Only create the mappings, do not index any data'
        )

    def handle(self, *args, **options):
        doc_classes = []
        for label in args:
            doc_classes.extend(app_documents.get(label, []))
        if not args:
            doc_classes.extend(documents)
        for doc_class in doc_classes:
            using = options['using'] or doc_class._doc_type.using or 'default'
            index = options['index'] or doc_class._doc_type.index or getattr(settings, 'SEEKER_INDEX', 'seeker')
            if options['keep']:
                doc_class.clear(index=index, using=using, keep_mapping=True)
            else:
                doc_class.clear(index=index, using=using)
                doc_class.init(index=index, using=using)
            if options['data']:
                reindex(doc_class, index, using, options)
            gc.collect()
