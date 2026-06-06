class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next


class SinglyLinkedList:
    def __init__(self):
        self.head = ListNode()  # dummy head

    def insert_after(self, node, val):
        node.next = ListNode(val, node.next)

    def delete_after(self, node):
        if node.next is None:
            return None
        removed = node.next
        node.next = removed.next
        removed.next = None
        return removed.val

    def to_list(self):
        cur, ans = self.head.next, []
        while cur:
            ans.append(cur.val)
            cur = cur.next
        return ans
