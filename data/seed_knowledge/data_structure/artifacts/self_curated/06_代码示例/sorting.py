def insertion_sort(a):
    a = list(a)
    for i in range(1, len(a)):
        x = a[i]
        j = i - 1
        while j >= 0 and a[j] > x:
            a[j + 1] = a[j]
            j -= 1
        a[j + 1] = x
    return a

def quick_sort(a):
    a = list(a)
    if len(a) <= 1:
        return a
    pivot = a[len(a) // 2]
    left = [x for x in a if x < pivot]
    mid = [x for x in a if x == pivot]
    right = [x for x in a if x > pivot]
    return quick_sort(left) + mid + quick_sort(right)

def merge_sort(a):
    a = list(a)
    if len(a) <= 1:
        return a
    mid = len(a) // 2
    left = merge_sort(a[:mid])
    right = merge_sort(a[mid:])
    i = j = 0
    ans = []
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            ans.append(left[i]); i += 1
        else:
            ans.append(right[j]); j += 1
    ans.extend(left[i:])
    ans.extend(right[j:])
    return ans
