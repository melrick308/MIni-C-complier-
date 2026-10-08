// title: Syntax errors (recovery)
// description: Three mistakes; the parser recovers and reports all of them.
// category: errors
int x = 5
int y = x * 2;
print(y)
if (y > 5 {
    print("big");
}
