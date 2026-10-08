// title: bool and void functions
// description: A function returning bool, used by a void function.
// category: functions
bool isEven(int n) {
    return n % 2 == 0;
}
void report(int n) {
    if (isEven(n)) {
        print(n, "is even");
    } else {
        print(n, "is odd");
    }
}
report(4);
report(7);
