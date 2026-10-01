// nvcc -arch=sm_70 -O2 cublas-test.cu -lcublas: runtime kernel + cuBLAS SGEMM/HGEMM vs CPU on the V100.
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <vector>
#include <cuda_runtime.h>
#include <cublas_v2.h>
#define CK(x) do { cudaError_t e = (x); if (e) { printf("FAIL %s: %s\n", #x, cudaGetErrorString(e)); return 1; } } while (0)
#define CB(x) do { cublasStatus_t s = (x); if (s) { printf("FAIL %s: %d\n", #x, (int)s); return 1; } } while (0)
__global__ void saxpy(int n, float a, const float *x, float *y) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) y[i] = a * x[i] + y[i];
}
int main() {
    cudaDeviceProp p; CK(cudaGetDeviceProperties(&p, 0));
    printf("%s sm_%d%d, %zu MB, %d SMs\n", p.name, p.major, p.minor, p.totalGlobalMem >> 20, p.multiProcessorCount);
    int n = 1 << 22; std::vector<float> x(n), y(n), r(n);
    for (int i = 0; i < n; i++) { x[i] = rand() / (float)RAND_MAX; y[i] = rand() / (float)RAND_MAX; }
    float *dx, *dy; CK(cudaMalloc(&dx, n * 4)); CK(cudaMalloc(&dy, n * 4));
    CK(cudaMemcpy(dx, x.data(), n * 4, cudaMemcpyHostToDevice)); CK(cudaMemcpy(dy, y.data(), n * 4, cudaMemcpyHostToDevice));
    saxpy<<<(n + 255) / 256, 256>>>(n, 2.5f, dx, dy); CK(cudaGetLastError());
    CK(cudaMemcpy(r.data(), dy, n * 4, cudaMemcpyDeviceToHost));
    int bad = 0; for (int i = 0; i < n; i++) if (fabsf(r[i] - (2.5f * x[i] + y[i])) > 1e-5f) bad++;
    printf("saxpy: %s (%d bad)\n", bad ? "FAIL" : "OK", bad);

    int N = 1024; std::vector<float> A(N * N), B(N * N), C(N * N), R(N * N, 0);
    for (auto &v : A) v = rand() / (float)RAND_MAX - 0.5f;
    for (auto &v : B) v = rand() / (float)RAND_MAX - 0.5f;
    for (int i = 0; i < N; i++) for (int k = 0; k < N; k++) { float a = A[k * N + i]; for (int j = 0; j < N; j++) R[j * N + i] += a * B[j * N + k]; }
    float *dA, *dB, *dC; CK(cudaMalloc(&dA, N * N * 4)); CK(cudaMalloc(&dB, N * N * 4)); CK(cudaMalloc(&dC, N * N * 4));
    CK(cudaMemcpy(dA, A.data(), N * N * 4, cudaMemcpyHostToDevice)); CK(cudaMemcpy(dB, B.data(), N * N * 4, cudaMemcpyHostToDevice));
    cublasHandle_t h; CB(cublasCreate(&h)); float one = 1, zero = 0;
    CB(cublasSgemm(h, CUBLAS_OP_N, CUBLAS_OP_N, N, N, N, &one, dA, N, dB, N, &zero, dC, N));
    CK(cudaMemcpy(C.data(), dC, N * N * 4, cudaMemcpyDeviceToHost));
    double me = 0; for (int i = 0; i < N * N; i++) me = fmax(me, fabs(C[i] - R[i]));
    printf("sgemm 1024: max err %.2e %s\n", me, me < 1e-3 ? "OK" : "FAIL");
    cudaEvent_t t0, t1; cudaEventCreate(&t0); cudaEventCreate(&t1);
    int M = 4096; float *eA, *eB, *eC; CK(cudaMalloc(&eA, (size_t)M * M * 4)); CK(cudaMalloc(&eB, (size_t)M * M * 4)); CK(cudaMalloc(&eC, (size_t)M * M * 4));
    CK(cudaMemset(eA, 0, (size_t)M * M * 4)); CK(cudaMemset(eB, 0, (size_t)M * M * 4));
    CB(cublasSgemm(h, CUBLAS_OP_N, CUBLAS_OP_N, M, M, M, &one, eA, M, eB, M, &zero, eC, M));
    cudaEventRecord(t0); for (int i = 0; i < 10; i++) CB(cublasSgemm(h, CUBLAS_OP_N, CUBLAS_OP_N, M, M, M, &one, eA, M, eB, M, &zero, eC, M));
    cudaEventRecord(t1); CK(cudaEventSynchronize(t1)); float ms; cudaEventElapsedTime(&ms, t0, t1);
    printf("sgemm 4096 x10: %.1f TFLOPS fp32\n", 10 * 2.0 * M * M * M / (ms / 1e3) / 1e12);
    CB(cublasGemmEx(h, CUBLAS_OP_N, CUBLAS_OP_N, M, M, M, &one, eA, CUDA_R_16F, M, eB, CUDA_R_16F, M, &zero, eC, CUDA_R_32F, M, CUBLAS_COMPUTE_32F, CUBLAS_GEMM_DEFAULT));
    cudaEventRecord(t0); for (int i = 0; i < 10; i++) CB(cublasGemmEx(h, CUBLAS_OP_N, CUBLAS_OP_N, M, M, M, &one, eA, CUDA_R_16F, M, eB, CUDA_R_16F, M, &zero, eC, CUDA_R_32F, M, CUBLAS_COMPUTE_32F, CUBLAS_GEMM_DEFAULT));
    cudaEventRecord(t1); CK(cudaEventSynchronize(t1)); cudaEventElapsedTime(&ms, t0, t1);
    printf("hgemm 4096 x10 (tensor cores): %.1f TFLOPS\n", 10 * 2.0 * M * M * M / (ms / 1e3) / 1e12);
    printf("%s\n", (bad == 0 && me < 1e-3) ? "ALL OK" : "FAILED");
    return 0;
}
