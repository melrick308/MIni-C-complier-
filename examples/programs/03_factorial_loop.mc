// title: Factorial (for loop)
// description: A for loop with a loop-scoped counter.
// category: loops
int n = 5;
int result = 1;
for (int i = 2; i <= n; i++) {
    result *= i;
}
print(n, "! =", result);
