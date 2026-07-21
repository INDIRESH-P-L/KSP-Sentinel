'use strict';

const catalyst = require('zcatalyst-sdk-node');

module.exports = async (req, res) => {
	const urlObj = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
	const pathname = urlObj.pathname;

	try {
		const catalystApp = catalyst.initialize(req);

		switch (pathname) {
			case '/':
				res.writeHead(200, { 'Content-Type': 'text/html' });
				res.write('<h1>Hello from index.js</h1>');
				break;

			case '/bulkwrite':
				const fileId = urlObj.searchParams.get('file_id');
				const tableName = urlObj.searchParams.get('table_name');
				const findBy = urlObj.searchParams.get('find_by');
				const operation = urlObj.searchParams.get('operation') || 'insert';

				if (!fileId || !tableName) {
					res.writeHead(400, { 'Content-Type': 'application/json' });
					res.write(JSON.stringify({ error: 'Missing file_id or table_name query parameters' }));
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

			case '/bulkjobstatus':
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

			default:
				res.writeHead(404, { 'Content-Type': 'text/plain' });
				res.write('Not Found');
				break;
		}
	} catch (error) {
		res.writeHead(500, { 'Content-Type': 'application/json' });
		res.write(JSON.stringify({ error: error.message || 'Internal Server Error' }));
	}
	res.end();
};
