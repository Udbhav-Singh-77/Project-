#include <stdio.h>

int main() {
    int number, sum = 0, hundred_digit = 0, temp, digit;
    do {
        printf("Enter a minimum 3-digit number: ");
        scanf("%d", &number);
    } while (number < 100);
    temp = number;
    while (temp > 0) {
        digit = temp % 10;
        sum += digit;
        temp /= 10;
    }
    hundred_digit = (number / 100) % 10;
    printf("Difference between sum of all digits and hundred's digit: %d\n", sum - hundred_digit);

    return 0;
}
