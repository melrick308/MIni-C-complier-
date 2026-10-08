// title: Max of three (nested calls)
// description: Functions calling functions, with arguments that are calls.
// category: functions
int max(int a, int b) {
    if (a > b) {
        return a;
    }
    return b;
}
int max3(int a, int b, int c) {
    return max(max(a, b), c);
}
print("max(4, 9, 7) =", max3(4, 9, 7));
