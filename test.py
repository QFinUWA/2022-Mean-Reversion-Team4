

def find_swing(data, window=5, high_low='high'):
    def find(x): return max(x) if high_low == 'high' else min(x)
    return find([r for r in reversed(data)][:window])


a = [1, 2, 3, 4, 6, 5, 3, -1, 0, 2, 3]
list = find_swing(a, high_low='high')
print(list)
