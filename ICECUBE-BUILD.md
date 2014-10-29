Building jzmq for the IceCube Maven repository
----------------------------------------------

Build on spts-access and package up the results of the build:

```./build &&
tar czf jzmq-jars.tgz target/classes target/*.jar
```

Build on OS X:

```./build```

Copy the `jzmq-jars.tgz` file from `spts-access` to the Mac and
extract the Linux-built files into the Mac's `target` subdirectory.

Run the `deploy` script to upload the files to IceCube's Maven repo.
