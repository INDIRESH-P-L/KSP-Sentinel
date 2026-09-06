'use strict';

const catalyst = require('zcatalyst-sdk-node');

// Mirrors IMPORT_OPERATIONS in backend/app/api/export.py. An unrecognised operation
// otherwise reaches the SDK and surfaces to the caller as an opaque upstream failure.
const ALLOWED_OPERATIONS = new Set(['insert', 'update', 'upsert']);

// Advanced I/O hands the raw (req, res) pair straight through, so every branch owns
// its own status line and the response is ended exactly once, at the bottom.
module.exports = async (req, res) => {
	let pathname = '/';

	try {
		// Only the path and query matter here, so the base is a constant: deriving it
		// from the Host header let a malformed (or spoofed) header break URL parsing.
		const urlObj = new URL(req.url || '/', 'http://localhost');
		pathname = urlObj.pathname;

		const catalystApp = catalyst.initialize(req);

		switch (pathname) {
			case '/': {
				res.writeHead(200, { 'Content-Type': 'text/html' });
				res.write('<h1>Hello from index.js</h1>');
				break;
			}

			case '/bulkwrite': {
				const fileId = urlObj.searchParams.get('file_id');
				const tableName = urlObj.searchParams.get('table_name');
				const findBy = urlObj.searchParams.get('find_by');
				const operation = urlObj.searchParams.get('operation') || 'insert';

				if (!fileId || !tableName) {
					res.writeHead(400, { 'Content-Type': 'application/json' });
					res.write(JSON.stringify({ error: 'Missing file_id or table_name query parameters' }));
					break;
				}

				if (!ALLOWED_OPERATIONS.has(operation)) {
					res.writeHead(400, { 'Content-Type': 'application/json' });
					res.write(JSON.stringify({
						error: `operation must be one of ${[...ALLOWED_OPERATIONS].join(', ')}`
					}));
					break;
				}

				const table = catalystApp.datastore().table(tableName);
				const bulkWrite = table.bulkJob('write');

				const options = { operation };
				if (findBy) {
					options.find_by = findBy;
				}

				const bulkWriteJob = await bulkWrite.createJob(fileId, options);
				const writejobid = bulkWriteJob.job_id;

				res.writeHead(200, { 'Content-Type': 'application/json' });
				res.write(JSON.stringify({
					status: 'success',
					job_id: writejobid,
					message: 'Bulk Write Job scheduled successfully!!'
				}));
				break;
			}

			case '/bulkjobstatus': {
				const jobId = urlObj.searchParams.get('job_id');
				const statusTableName = urlObj.searchParams.get('table_name');

				if (!jobId || !statusTableName) {
					res.writeHead(400, { 'Content-Type': 'application/json' });
					res.write(JSON.stringify({ error: 'Missing job_id or table_name query parameters' }));
					break;
				}

				const statusTable = catalystApp.datastore().table(statusTableName);
				const bulkJobStatus = statusTable.bulkJob('write');
				const writeStatus = await bulkJobStatus.getStatus(jobId);

				res.writeHead(200, { 'Content-Type': 'application/json' });
				res.write(JSON.stringify({
					status: 'success',
					job_status: writeStatus
				}));
				break;
			}

			default: {
				res.writeHead(404, { 'Content-Type': 'text/plain' });
				res.write('Not Found');
				break;
			}
		}
	} catch (error) {
		// Datastore errors quote table and column internals, so the detail stays in the
		// Catalyst function logs and the caller gets a fixed string.
		console.error(`ksp_sentinel_function failed on ${pathname}:`, error);
		// A throw after writeHead would otherwise raise ERR_HTTP_HEADERS_SENT here and
		// leave the connection hanging without the res.end() below.
		if (!res.headersSent) {
			res.writeHead(500, { 'Content-Type': 'application/json' });
			res.write(JSON.stringify({ error: 'Internal Server Error' }));
		}
	}
	res.end();
};
