module github.com/example/project

go 1.22

require (
	github.com/foo/bar v1.0.0
	github.com/baz/qux v0.5.0
)

replace (
	github.com/foo/bar => ../bar
	github.com/baz/qux => github.com/fork/qux v0.5.1
)

exclude github.com/old/pkg v0.1.0
