// title: Factorial (recursive)
// description: A recursive function: watch the call stack grow in the debugger.
// category: functions
int fact(int n) {
    if (n <= 1) {
        return 1;
    }
    return n * fact(n - 1);
}
print("5! =", fact(5));
print("10! =", fact(10));
