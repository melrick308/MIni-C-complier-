// title: int vs float
// description: Integer division truncates; int widens to float automatically.
// category: types
int a = 7;
int b = 2;
float c = 7.0;
print("7 / 2 =", a / b);
print("7 % 2 =", a % b);
print("7.0 / 2 =", c / b);
float widened = a;
print("widened =", widened);
print("-7 / 2 =", -a / b);
