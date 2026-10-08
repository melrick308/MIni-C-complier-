// title: Short-circuit evaluation
// description: && and || skip the right side when the result is already known.
// category: conditions
int x = 0;
bool safe = x != 0 && 10 / x > 1;
print("safe =", safe);
bool either = x == 0 || 10 / x > 1;
print("either =", either);
