export default function pFinally<T>(promise: PromiseLike<T>, onFinally: () => unknown) {
    return Promise.resolve(promise).finally(() => {
        onFinally()
    })
}
