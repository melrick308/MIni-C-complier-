// title: Dangling else
// description: 'else' binds to the nearest 'if' - check the AST.
// category: conditions
int x = 5;
int y = -3;
if (x > 0)
    if (y > 0)
        print("both positive");
    else
        print("x positive, y not");
