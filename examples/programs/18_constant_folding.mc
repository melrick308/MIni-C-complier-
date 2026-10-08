// title: Optimizer showcase
// description: Turn on Optimize to see constant folding and dead code removal.
// category: optimizer
int seconds = 60 * 60 * 24;
int x = 2 * 3 + 4;
int y = x * 1 + 0;
if (1 > 2) {
    print("never");
}
print(seconds, x, y);
