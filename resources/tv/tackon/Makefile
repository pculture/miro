CC = gcc
STRIP = strip

tackon.dll: tackon.c tackon.h
	$(CC) tackon.c ../Source/crc32.c -O3 -shared -I ../Source -mno-cygwin -o tackon.dll
	$(STRIP) tackon.dll

clean:
	rm tackon.dll
