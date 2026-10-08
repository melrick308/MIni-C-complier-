// title: Sum 1..N (while loop)
// description: A while loop with an accumulator, += and ++.
// category: loops
int n = 10;
int sum = 0;
int i = 1;
while (i <= n) {
    sum += i;
    i++;
}
print("sum of 1 ..", n, "=", sum);
