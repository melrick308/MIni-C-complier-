// title: FizzBuzz
// description: An if / else-if chain inside a loop.
// category: conditions
for (int i = 1; i <= 15; i++) {
    if (i % 15 == 0) {
        print("FizzBuzz");
    } else if (i % 3 == 0) {
        print("Fizz");
    } else if (i % 5 == 0) {
        print("Buzz");
    } else {
        print(i);
    }
}
