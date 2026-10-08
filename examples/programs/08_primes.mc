// title: Prime numbers (nested loops + break)
// description: Nested loops; break leaves the inner loop early.
// category: loops
int count = 0;
for (int n = 2; n <= 30; n++) {
    bool isPrime = true;
    for (int d = 2; d * d <= n; d++) {
        if (n % d == 0) {
            isPrime = false;
            break;
        }
    }
    if (isPrime) {
        print(n);
        count++;
    }
}
print("primes found:", count);
