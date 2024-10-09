// REQUIRES: host-has-at-least-1-gpus
// REQUIRES: all-gpus-support-fp8
// RUN: mlir-tensorrt-opt %s -convert-memref-to-cuda -convert-plan-to-executor -convert-cuda-to-executor -executor-lowering-pipeline \
// RUN:   | mlir-tensorrt-translate -mlir-to-runtime-executable \
// RUN:   | mlir-tensorrt-runner -input-type=rtexe | FileCheck %s

!descriptor1D = !executor.table<!executor.ptr<device>, !executor.ptr<device>, index, index, index>
!hostMemRef = memref<4xf8E4M3FN, #plan.memory_space<host_pinned>>
!devMemRef = memref<4xf8E4M3FN, #plan.memory_space<device>>


memref.global @host_buffer : !hostMemRef = dense<0.0>
memref.global @cuda_buffer : !devMemRef = dense<0.0>

func.func @main() -> i32{
  %c0 = arith.constant 0 : i32
  %c0_index = arith.constant 0 : index
  %c1 = arith.constant 1 : i32
  %c1_index = arith.constant 1 : index
  %c4 = arith.constant 4 : index
  %c16 = arith.constant 16 : index

  %num_cuda_devices = cuda.num_devices : i32
  %has_cuda_device = arith.cmpi sge, %num_cuda_devices, %c1 : i32

  executor.print "found %d cuda devices"(%num_cuda_devices : i32)

  %0 = scf.if %has_cuda_device -> i32 {
    executor.print "start!"()
    %host_memref = memref.alloc() : !hostMemRef
    %device_memref = memref.get_global @cuda_buffer: !devMemRef

    %c1f = arith.constant 0.395264 : f8E4M3FN

    // Fill the host buffer.
    scf.for %i = %c0_index to %c4 step %c1_index {
       memref.store %c1f, %host_memref[%i] : !hostMemRef
    }

    // Copy host -> device then device -> host
    memref.copy %host_memref , %device_memref : !hostMemRef to !devMemRef
    memref.copy %device_memref , %host_memref : !devMemRef to !hostMemRef
    // Deallocate
    memref.dealloc %device_memref : !devMemRef

    // Print the host buffer
    scf.for %i = %c0_index to %c4 step %c1_index {
      %value = memref.load %host_memref[%i] : !hostMemRef
      executor.print "host_memref[%i] = %s"(%i, %value : index, f8E4M3FN)
    }

    memref.dealloc %host_memref : !hostMemRef

    executor.print "done!"()
    scf.yield %c0 : i32
  } else {
    executor.print "no cuda devices"()
    scf.yield %c1 : i32
  }
  return %0 : i32
}

// CHECK: found {{[0-9]+}} cuda devices
// CHECK: start!
// CHECK: host_memref[0] = 0.40625
// CHECK: host_memref[1] = 0.40625
// CHECK: host_memref[2] = 0.40625
// CHECK: host_memref[3] = 0.40625
// CHECK: done!