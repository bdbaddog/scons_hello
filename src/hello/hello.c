#include <stdio.h>
#ifdef PHRASE
#define STR_(x) #x
#define STR(x) STR_(x)
#define PUT_STR STR(PHRASE)
#else
#define PUT_STR "Hello World"
#endif
#ifdef EXCLAIM
#undef EXCLAIM
#define EXCLAIM "!"
#else
#define EXCLAIM
#endif


int main()
{
   puts(PUT_STR EXCLAIM);
   return 0x00;
}

