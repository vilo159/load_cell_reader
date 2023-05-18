class TestSingleton:
    class __TestSingleton:
        def __init__(self):
            self.clear_all()
        def clear_all(self):        
            self.datasets = []
    instance = None
    def __init__(self):
        if not TestSingleton.instance:
            TestSingleton.instance = TestSingleton.__TestSingleton()

    def clear_all(self):
        self.instance.clear_all()

    def get_timestamp(self):
        return self.instance.timestamp
    def set_timestamp(self, timestamp):
        self.instance.timestamp = timestamp

    def get_datasets(self):
        return self.instance.datasets
    def set_datasets(self, datasets):
        self.instance.datasets = datasets
