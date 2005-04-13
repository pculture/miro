all:
	python setup.py build

install:
	python setup.py install

clean:
	$(RM) -rf build

link:
	gcc -pthread -shared build/temp.linux-i686-2.3/vlcmodule.o build/temp.linux-i686-2.3/mediacontrol-init.o build/temp.linux-i686-2.3/mediacontrol-core.o /usr/lib/libtheora.a /usr/local/lib/libx264.a -L/usr/lib/vlc -L/usr/lib -lvlc -lrt -ldl -lpthread -lm -li420_rgb_mmx -li420_yuy2_mmx -li420_ymga_mmx -li422_yuy2_mmx -lfaad -lavcodec -lavformat -lhal -ldbus-1 -ltheora -lx264 -lfaad -lmux_ts -ldvbpsi -lpostproc -lmemcpymmx -lmemcpymmxext -lmemcpy3dn /usr/local/lib/libfaad.a /usr/lib/libtheora.a /usr/local/lib/libx264.a -lavcodec -o build/lib.linux-i686-2.3/vlc.so -fpic -fPIC

