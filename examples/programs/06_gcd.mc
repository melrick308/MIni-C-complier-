// title: Greatest common divisor
// description: Euclid's algorithm with while and %.
// category: functions
int gcd(int a, int b) {
    while (b != 0) {
        int r = a % b;
        a = b;
        b = r;
    }
    return a;
}
print("gcd(48, 18) =", gcd(48, 18));
print("gcd(17, 5) =", gcd(17, 5));
