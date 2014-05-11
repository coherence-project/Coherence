import rhythmdb


class CoherenceDBEntryType(rhythmdb.EntryType):
    def __init__(self, client_id):
        entry_name = "CoherenceUpnp:%s", client_id
        rhythmdb.EntryType.__init__(self, name=entry_name)
