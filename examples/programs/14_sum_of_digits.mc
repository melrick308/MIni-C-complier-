// title: Sum of digits
// description: A while loop using % and /= on a parameter.
// category: functions
int digitSum(int n) {
    int s = 0;
    while (n > 0) {
        s += n % 10;
        n /= 10;
    }
    return s;
}
print("digit sum of 12345 =", digitSum(12345));
