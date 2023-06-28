#!/bin/bash

cd ..

if [ ! -d "HybridAGI-library" ]; then
  git clone https://github.com/SynaLinks/HybridAGI-library
else
  cd HybridAGI-library
  git pull
  cd ..
fi

cd HybridAGI