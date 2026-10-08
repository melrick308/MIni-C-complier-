// title: Infinite loop (step limit)
// description: The VM stops runaway programs after 100,000 instructions.
// category: runtime
int i = 0;
while (true) {
    i++;
}
