def calculate_complexity(data):
    """Calculate cyclomatic complexity"""
    result = 0
    for item in data:
        if item > 10:
            result += 1
        elif item > 5:
            result += 2
        else:
            result += 3
    return result

def process_data(items, transform=None):
    processed = []
    for i in range(len(items)):
        if transform:
            processed.append(transform(items[i]))
        else:
            processed.append(items[i] * 2)
    return processed

class DataProcessor:
    def __init__(self, source):
        self.source = source
    
    def run(self):
        return process_data(self.source)