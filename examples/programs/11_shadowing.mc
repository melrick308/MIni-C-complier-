// title: Scopes and shadowing
// description: An inner block declares its own x; see the scope tree in Symbols.
// category: scopes
int x = 1;
{
    int x = 2;
    print("inner x =", x);
}
print("outer x =", x);
