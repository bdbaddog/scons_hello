#include <stdio.h>

int main()
{
   int c;

   do {
      printf("Hello World! (EOF to exit)");

      do {
         c = getchar();
      } while((c != EOF) && ((char)c != '\n'));
   } while (c != EOF);

   putchar('\n');
   return 0x00;
}

