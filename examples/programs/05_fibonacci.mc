// title: Fibonacci numbers
// description: A for loop that updates several variables each iteration.
// category: loops
int a = 0;
int b = 1;
for (int i = 0; i < 10; i++) {
    print(a);
    int next = a + b;
    a = b;
    b = next;
}
